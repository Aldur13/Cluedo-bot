"""Mystery Progress panel: a filled-bar summary of `MysteryProgress` --
known/total cards as a percentage, remaining valid worlds, turns played, and
chance of solving next turn.

Uses a plain `tk.Canvas`-drawn bar rather than `ttk.Progressbar` so the fill
color always follows the active `Theme` (ttk's platform-native styling makes
per-theme recoloring unreliable on Windows).
"""
from __future__ import annotations

import tkinter as tk

from cluedo.mystery_progress import compute_mystery_progress

_BAR_WIDTH = 260
_BAR_HEIGHT = 18


def build(parent, theme) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    box = tk.LabelFrame(frame, text="Mystery Progress", font=theme.body_font(11), bg=theme.panel_bg)
    box.pack(fill="x")

    body = tk.Frame(box, bg=theme.panel_bg)
    body.pack(fill="x", padx=8, pady=8)

    bar_canvas = tk.Canvas(
        body, width=_BAR_WIDTH, height=_BAR_HEIGHT, bg=theme.unknown, highlightthickness=0
    )
    bar_canvas.pack(anchor="w", pady=(0, 4))
    bar_fill = bar_canvas.create_rectangle(0, 0, 0, _BAR_HEIGHT, fill=theme.accent, width=0)
    bar_text = bar_canvas.create_text(
        _BAR_WIDTH / 2, _BAR_HEIGHT / 2, text="", fill=theme.text, font=theme.body_font(8, "bold")
    )

    info_label = tk.Label(
        body, text="", justify="left", bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
    )
    info_label.pack(anchor="w")

    def refresh(game_state):
        if game_state is None:
            bar_canvas.coords(bar_fill, 0, 0, 0, _BAR_HEIGHT)
            bar_canvas.itemconfig(bar_text, text="")
            info_label.config(text="No game in progress.")
            return

        progress = compute_mystery_progress(game_state)

        pct = (progress.known_cards / progress.total_cards) if progress.total_cards else 0.0
        pct = max(0.0, min(1.0, pct))
        fill_width = _BAR_WIDTH * pct
        bar_canvas.coords(bar_fill, 0, 0, fill_width, _BAR_HEIGHT)
        bar_canvas.itemconfig(
            bar_fill, fill=theme.confirmed if pct >= 0.999 else theme.accent
        )
        bar_canvas.itemconfig(bar_text, text=f"{progress.known_cards}/{progress.total_cards} known ({pct * 100:.0f}%)")

        worlds_text = (
            "unknown" if progress.remaining_valid_worlds is None else f"{progress.remaining_valid_worlds:,}"
        )
        chance_text = (
            "N/A" if progress.chance_of_solving_next_turn is None
            else f"{progress.chance_of_solving_next_turn * 100:.0f}%"
        )
        info_label.config(
            text=(
                f"Remaining valid worlds: {worlds_text}\n"
                f"Turns played: {progress.turns_played}\n"
                f"Chance of solving next turn: {chance_text}"
            )
        )

    frame.refresh = refresh
    refresh(None)
    return frame
