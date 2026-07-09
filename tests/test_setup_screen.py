"""Tests for cluedo/gui/setup_screen.py."""
import tkinter as tk

from cluedo.gui import setup_screen
from cluedo.gui.theme import LIGHT


def _find_all(widget, predicate):
    found = []
    for child in widget.winfo_children():
        if predicate(child):
            found.append(child)
        found.extend(_find_all(child, predicate))
    return found


def _confirm_button(frame):
    return next(
        w for w in _find_all(frame, lambda w: isinstance(w, tk.Button))
        if "Continue" in str(w.cget("text"))
    )


def test_non_numeric_hand_size_shows_error_instead_of_crashing(root, cfg, monkeypatch):
    # Regression: count_var/hand_vars are tk.IntVars bound to freely-editable
    # Spinboxes with no validatecommand. Typing non-numeric text into one and
    # clicking Continue used to raise an uncaught _tkinter.TclError instead of
    # the same messagebox.showerror validation every other bad-input case here
    # gets.
    errors = []
    monkeypatch.setattr(
        setup_screen.messagebox, "showerror", lambda title, message: errors.append((title, message))
    )
    confirmed = []
    frame = setup_screen.build(root, LIGHT, cfg, lambda players, you: confirmed.append((players, you)))
    try:
        root.update_idletasks()

        spinboxes = _find_all(frame, lambda w: isinstance(w, tk.Spinbox))
        assert spinboxes, "expected at least one Spinbox (player count + hand sizes)"
        hand_spinbox = spinboxes[-1]  # last row's hand-size spinbox
        hand_spinbox.delete(0, "end")
        hand_spinbox.insert(0, "3x")

        _confirm_button(frame).invoke()

        assert not confirmed
        assert errors and errors[0][0] == "Invalid number"
    finally:
        frame.destroy()
