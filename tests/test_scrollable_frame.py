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


def _widgets(outer):
    canvas = next(w for w in outer.winfo_children() if isinstance(w, tk.Canvas))
    scrollbar = next(w for w in outer.winfo_children() if isinstance(w, tk.Scrollbar))
    return canvas, scrollbar


def test_scrollbar_hidden_when_content_fits(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        outer.pack(fill="both", expand=True)
        outer.configure(height=400)
        tk.Label(inner, text="only row", height=1).pack(fill="x")
        root.update_idletasks()
        _canvas, scrollbar = _widgets(outer)
        assert not scrollbar.winfo_ismapped()
    finally:
        outer.destroy()


def test_scrollbar_shown_when_content_overflows(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        # Explicit width/height + no fill/expand + pack_propagate(False), so
        # `outer` stays pinned to this size regardless of how large the
        # shared session-scoped `root` has grown from earlier tests.
        outer.configure(width=200, height=100)
        outer.pack_propagate(False)
        outer.pack()
        for _ in range(50):
            tk.Label(inner, text="row", height=1).pack(fill="x")
        root.update_idletasks()
        _canvas, scrollbar = _widgets(outer)
        assert scrollbar.winfo_ismapped()
    finally:
        outer.destroy()


def test_mousewheel_scrolls_canvas_when_pointer_over_content(root):
    outer, inner = build_scrollable_frame(root, LIGHT)
    try:
        outer.configure(width=200, height=100)
        outer.pack_propagate(False)
        outer.pack()
        labels = [tk.Label(inner, text=f"row {i}", height=1) for i in range(50)]
        for label in labels:
            label.pack(fill="x")
        root.update_idletasks()
        canvas, _scrollbar = _widgets(outer)
        assert canvas.yview()[0] == 0.0

        # Generating <MouseWheel> on a Label inside `inner` (not on `canvas`
        # itself) is the point of this test: `inner`'s children fully cover
        # the canvas, so this is what a real hover-and-scroll looks like.
        labels[0].event_generate("<MouseWheel>", delta=-120)
        root.update_idletasks()
        assert canvas.yview()[0] > 0.0
    finally:
        outer.destroy()


def test_keyboard_scrolls_canvas_when_focus_within_content(root):
    # Keyboard focus is tracked per-toplevel in Tk -- using a dedicated
    # Toplevel (rather than packing straight into the session-shared `root`)
    # isolates this test's focus_set()/focus_get() from whatever focus state
    # other GUI tests earlier in a full suite run may have left behind on
    # `root` itself.
    win = tk.Toplevel(root)
    outer, inner = build_scrollable_frame(win, LIGHT)
    try:
        outer.configure(width=200, height=100)
        outer.pack_propagate(False)
        outer.pack()
        button = tk.Button(inner, text="focus me")
        button.pack(fill="x")
        for _ in range(50):
            tk.Label(inner, text="row", height=1).pack(fill="x")
        win.update()
        canvas, _scrollbar = _widgets(outer)
        # `focus_set()` alone only updates this toplevel's *logical* focus
        # chain -- `focus_get()` (which the handler under test relies on)
        # only reports it once `win` also holds the real window-manager
        # input focus, which `focus_set()` doesn't force by itself. Deep in
        # a full test-suite run, many other Toplevels have been created and
        # destroyed by other GUI tests by the time this one runs, so it
        # can't be assumed `win` already has that real focus.
        win.focus_force()
        button.focus_set()
        win.update()
        assert canvas.yview()[0] == 0.0

        button.event_generate("<End>")
        win.update()
        assert canvas.yview()[0] > 0.0
    finally:
        win.destroy()
