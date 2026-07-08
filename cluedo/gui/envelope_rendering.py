"""Shared probability-bar rendering for Envelope Analysis (the sidebar
panel, `cluedo/gui/panels/envelope_probabilities_panel.py`) and Envelope
Explorer (the standalone screen, `cluedo/gui/envelope_explorer_screen.py`)
-- factored out so the two don't duplicate the same bar-drawing code.
"""
from __future__ import annotations

import tkinter as tk

_BAR_HEIGHT = 12


def bar_color(theme, p: float) -> str:
    return theme.confirmed if p >= 0.999 else theme.accent


def render_probability_row(container, theme, name: str, p: float, *, bar_width: int = 130) -> tk.Frame:
    """Renders one "name [====    ] NN%" row into `container` and returns the
    row Frame, so callers that need to add more content below it (e.g. a
    trend sparkline) can pack into the same row or its parent afterward."""
    row = tk.Frame(container, bg=theme.panel_bg)
    row.pack(fill="x", pady=1)
    tk.Label(
        row, text=name, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9), width=14, anchor="w",
    ).pack(side="left")
    canvas = tk.Canvas(row, width=bar_width, height=_BAR_HEIGHT, bg=theme.unknown, highlightthickness=0)
    canvas.pack(side="left", padx=(4, 6))
    canvas.create_rectangle(
        0, 0, bar_width * max(0.0, min(1.0, p)), _BAR_HEIGHT, fill=bar_color(theme, p), width=0
    )
    tk.Label(
        row, text=f"{p * 100:.0f}%", bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9), width=5,
    ).pack(side="left")
    return row


def render_sparkline(container, theme, values: list, *, width: int = 90, height: int = 20) -> tk.Canvas:
    """Small canvas-drawn line chart of `values` (each `Optional[float]` in
    [0, 1], `None` entries skipped) -- no matplotlib import for something
    this small, matching this project's existing plain-Canvas-bar
    convention (see mystery_progress_panel.py's docstring)."""
    canvas = tk.Canvas(container, width=width, height=height, bg=theme.panel_bg, highlightthickness=0)
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(points) >= 2:
        n = len(values)
        coords = []
        for i, v in points:
            x = (i / max(1, n - 1)) * width
            y = height - v * height
            coords.extend([x, y])
        canvas.create_line(*coords, fill=theme.accent, width=1)
    return canvas
