"""Tests for cluedo/gui/settings_screen.py: theme picker wiring and the
cross-game learning opt-out toggle.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.gui import settings_screen
from cluedo.gui.theme import DARK, LIGHT, ThemeManager


class _FakeStore:
    def __init__(self, enabled=True):
        self._enabled = enabled
        self.reset_calls = 0

    def is_learning_enabled(self):
        return self._enabled

    def set_learning_enabled(self, value):
        self._enabled = value

    def reset_all_data(self):
        self.reset_calls += 1


class _FakeApp:
    def __init__(self, root):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.player_store = _FakeStore()


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_settings did not create a Toplevel")


def _radiobuttons(widget):
    found = []
    if isinstance(widget, tk.Radiobutton):
        found.append(widget)
    for child in widget.winfo_children():
        found.extend(_radiobuttons(child))
    return found


def test_picking_dark_theme_calls_set_theme(root):
    app = _FakeApp(root)

    settings_screen.open_settings(app)
    win = _find_toplevel(root)
    try:
        dark_button = next(b for b in _radiobuttons(win) if str(b.cget("value")) == "dark")
        dark_button.invoke()
        assert app.theme_manager.current is DARK
    finally:
        # on_theme_pick destroys and reopens the window on pick; close whichever is live now.
        _find_toplevel(root).destroy()


def test_learning_checkbox_reflects_and_updates_store_state(root):
    app = _FakeApp(root)
    app.player_store = _FakeStore(enabled=True)

    settings_screen.open_settings(app)
    win = _find_toplevel(root)
    try:
        checkbutton = next(
            w for w in win.winfo_children() if isinstance(w, tk.Checkbutton)
        )
        checkbutton.invoke()  # toggles True -> False
        assert app.player_store.is_learning_enabled() is False
        checkbutton.invoke()  # toggles False -> True
        assert app.player_store.is_learning_enabled() is True
    finally:
        win.destroy()


def test_reset_button_calls_reset_all_data(root):
    app = _FakeApp(root)

    settings_screen.open_settings(app)
    win = _find_toplevel(root)
    try:
        reset_button = next(
            w for w in win.winfo_children()
            if isinstance(w, tk.Button) and "Reset" in str(w.cget("text"))
        )
        reset_button.invoke()
        assert app.player_store.reset_calls == 1
    finally:
        win.destroy()
