"""Game Statistics panel: turns logged, confirmed cards, ambiguous cards,
valid worlds, propagation iterations, and last solve time -- the same data
main_screen.py's old inline "Statistics" box showed, laid out more cleanly as
a label/value grid instead of one preformatted text blob.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.gui.widgets import CollapsibleCard


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Statistics", key="statistics")
    card.pack(fill="x")
    grid = card.body

    _ROWS = (
        "Suggestions logged",
        "Confirmed cards",
        "Ambiguous cards",
        "Valid worlds (last count)",
        "Propagation iterations",
        "Last solve time",
    )

    value_labels = {}
    for r, name in enumerate(_ROWS):
        tk.Label(
            grid, text=f"{name}:", bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9), anchor="w",
        ).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=1)
        value = tk.Label(grid, text="", bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9, "bold"), anchor="w")
        value.grid(row=r, column=1, sticky="w", pady=1)
        value_labels[name] = value

    def refresh(game_state):
        if game_state is None:
            for label in value_labels.values():
                label.config(text="—")
            return

        sheet = game_state.detective_sheet()
        stats = game_state.last_solver_stats
        confirmed_count = sum(1 for v in sheet.values() if v["status"] == "confirmed")

        value_labels["Suggestions logged"].config(text=str(len(game_state.history)))
        value_labels["Confirmed cards"].config(text=f"{confirmed_count}/{len(game_state.cards)}")
        value_labels["Ambiguous cards"].config(text=str(stats.ambiguous_card_count_last))
        value_labels["Valid worlds (last count)"].config(
            text="unknown" if stats.valid_worlds_last_counted is None else f"{stats.valid_worlds_last_counted:,}"
        )
        value_labels["Propagation iterations"].config(text=str(stats.propagation_iterations))
        value_labels["Last solve time"].config(text=f"{stats.wall_clock_seconds * 1000:.1f} ms")

    frame.refresh = refresh
    refresh(None)
    return frame
