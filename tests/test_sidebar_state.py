"""Tests for cluedo/gui/sidebar_state.py -- the plain module-level dict
backing CollapsibleCard expand/collapse state and per-card Show All/Show
Why flags. tests/conftest.py's autouse `_reset_sidebar_state` fixture
clears both dicts before and after every test, so these don't need to.
"""
from cluedo.gui import sidebar_state


def test_get_expanded_defaults_true_until_set():
    assert sidebar_state.get_expanded("some_card") is True
    sidebar_state.set_expanded("some_card", False)
    assert sidebar_state.get_expanded("some_card") is False
    sidebar_state.set_expanded("some_card", True)
    assert sidebar_state.get_expanded("some_card") is True


def test_get_expanded_respects_custom_default():
    assert sidebar_state.get_expanded("unset_card", default=False) is False


def test_flags_default_false_until_set():
    assert sidebar_state.get_flag("show_all.suspects") is False
    sidebar_state.set_flag("show_all.suspects", True)
    assert sidebar_state.get_flag("show_all.suspects") is True


def test_toggle_flag_flips_and_returns_new_value():
    assert sidebar_state.get_flag("show_why") is False
    first = sidebar_state.toggle_flag("show_why")
    assert first is True
    assert sidebar_state.get_flag("show_why") is True
    second = sidebar_state.toggle_flag("show_why")
    assert second is False
    assert sidebar_state.get_flag("show_why") is False


def test_keys_are_independent():
    sidebar_state.set_expanded("card_a", False)
    sidebar_state.set_expanded("card_b", True)
    assert sidebar_state.get_expanded("card_a") is False
    assert sidebar_state.get_expanded("card_b") is True
