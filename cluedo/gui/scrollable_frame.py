"""Reusable Canvas+Scrollbar+inner-Frame scrolling idiom.

Extracted so new call sites don't hand-duplicate the pattern already
present (independently) in game_review_screen.py, sheet_grid.py, and
suggestion_dialog.py -- those three existing call sites are left as-is;
this is for new call sites, starting with main_screen.py's sidebar.
"""
from __future__ import annotations

import tkinter as tk


def build_scrollable_frame(parent, theme) -> tuple[tk.Frame, tk.Frame]:
    """Returns (outer, inner). Pack/grid `outer` in the caller's layout;
    pack content into `inner` exactly as if it were a plain Frame -- it
    scrolls automatically once its content overflows the visible area.
    `inner`'s width is kept in sync with the canvas's visible width, so
    `fill="x"` children span the full scrollable width rather than
    shrink-wrapping to their natural size.
    """
    outer = tk.Frame(parent, bg=theme.bg)

    canvas = tk.Canvas(outer, bg=theme.bg, highlightthickness=0)
    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    inner = tk.Frame(canvas, bg=theme.bg)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_configure(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfig(window_id, width=event.width)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    return outer, inner
