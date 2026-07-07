"""Tests for cluedo.gui.widgets.CollapsibleCard -- the sidebar's card chrome.

Uses the session-scoped `root` fixture from tests/conftest.py; the
autouse `_reset_sidebar_state` fixture keeps expand/collapse state from
leaking between tests.
"""
from cluedo.gui import sidebar_state
from cluedo.gui.theme import LIGHT
from cluedo.gui.widgets import CollapsibleCard


def test_card_starts_expanded_by_default(root):
    card = CollapsibleCard(root, LIGHT, title="Test Card", key="test_card")
    try:
        assert card.body.winfo_manager() == "pack"
        assert card._toggle_label.cget("text") == "▾"
    finally:
        card.frame.destroy()


def test_card_starts_collapsed_if_state_says_so(root):
    sidebar_state.set_expanded("test_card_collapsed", False)
    card = CollapsibleCard(root, LIGHT, title="Test Card", key="test_card_collapsed")
    try:
        assert card.body.winfo_manager() == ""
        assert card._toggle_label.cget("text") == "▸"
    finally:
        card.frame.destroy()


def test_toggle_collapses_and_re_expands(root):
    card = CollapsibleCard(root, LIGHT, title="Test Card", key="test_card_toggle")
    try:
        assert card.body.winfo_manager() == "pack"
        card.toggle()
        assert card.body.winfo_manager() == ""
        assert sidebar_state.get_expanded("test_card_toggle") is False
        card.toggle()
        assert card.body.winfo_manager() == "pack"
        assert sidebar_state.get_expanded("test_card_toggle") is True
    finally:
        card.frame.destroy()


def test_header_click_toggles(root):
    card = CollapsibleCard(root, LIGHT, title="Test Card", key="test_card_click")
    try:
        card.pack()
        root.update()
        # Invoke the bound <Button-1> handler directly with explicit
        # coordinates/when="now" -- relying on event_generate's synthetic
        # delivery alone is unreliable for an unmapped, off-screen test
        # window (see tests/test_sheet_grid.py's same workaround).
        card.title_label.event_generate("<Button-1>", x=1, y=1, when="now")
        assert card.body.winfo_manager() == ""
    finally:
        card.frame.destroy()


def test_title_label_carries_card_title_text(root):
    card = CollapsibleCard(root, LIGHT, title="My Title", key="test_card_title")
    try:
        assert card.title_label.card_title_text == "My Title"
    finally:
        card.frame.destroy()


def test_disclaimer_is_rendered_in_body(root):
    card = CollapsibleCard(root, LIGHT, title="Advisory", key="test_card_disclaimer", disclaimer="Not certain.")
    try:
        texts = [str(w.cget("text")) for w in card.body.winfo_children()]
        assert any("Not certain." in t for t in texts)
    finally:
        card.frame.destroy()
