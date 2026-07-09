"""Tests for cluedo/gui/app.py's global keyboard-shortcut focus guard."""
import tkinter as tk

from cluedo.gui.app import App


def _bare_app(root):
    app = App.__new__(App)
    app.root = root
    return app


def test_guarded_action_is_skipped_while_entry_has_focus(root):
    # Regression: root.bind_all("<Control-z>", ...) fires regardless of
    # focus. Tk's built-in Entry bindings only claim Ctrl-A/B/D/E/F/H/K/T/W
    # -- not Z/S/O/N/E/R -- so typing e.g. Ctrl-Z while editing a value in a
    # dialog Entry used to silently call app.undo() (deleting the player's
    # last logged suggestion) instead of editing text.
    app = _bare_app(root)
    calls = []
    handler = app._guarded(lambda: calls.append(1))

    entry = tk.Entry(root)
    entry.pack()
    entry.focus_force()
    root.update()

    handler(None)
    assert calls == []

    entry.destroy()


def test_guarded_action_fires_when_focus_elsewhere(root):
    app = _bare_app(root)
    calls = []
    handler = app._guarded(lambda: calls.append(1))

    button = tk.Button(root, text="focus me")
    button.pack()
    button.focus_force()
    root.update()

    handler(None)
    assert calls == [1]

    button.destroy()
