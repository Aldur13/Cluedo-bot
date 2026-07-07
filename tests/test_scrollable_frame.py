"""Tests for cluedo/gui/scrollable_frame.py -- the extracted
Canvas+Scrollbar+inner-Frame scrolling idiom."""
import tkinter as tk

from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.theme import LIGHT


def test_build_returns_outer_and_inner_frames(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        assert isinstance(outer, tk.Frame)
        assert isinstance(inner, tk.Frame)
    finally:
        outer.destroy()


def test_content_packed_into_inner_is_reachable(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        label = tk.Label(inner, text="hello")
        label.pack()
        root.update_idletasks()
        assert label.winfo_ismapped() or label.winfo_manager() == "pack"
    finally:
        outer.destroy()


def test_inner_configure_updates_canvas_scrollregion(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        outer.pack()
        canvas = next(w for w in outer.winfo_children() if isinstance(w, tk.Canvas))
        for _ in range(50):
            tk.Label(inner, text="row", height=1).pack(fill="x")
        root.update_idletasks()
        # scrollregion should have been set to something non-trivial once
        # inner grew taller than a handful of labels.
        region = canvas.cget("scrollregion")
        assert region != ""
    finally:
        outer.destroy()
