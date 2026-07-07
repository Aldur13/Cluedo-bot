"""Endgame panel: surfaces `cluedo.analysis.endgame.suggest_accusation_readiness`.
Styled like ai_insights_panel.py -- accent-colored heading, never
theme.confirmed green for the "not yet safe" state -- except once the game
is actually solved, where the message *is* an exact solver fact and gets the
same solved-green treatment the rest of the dashboard uses for confirmed facts.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.endgame import suggest_accusation_readiness


def build(parent, theme) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    box = tk.LabelFrame(
        frame, text="Endgame", font=theme.body_font(11), bg=theme.panel_bg, fg=theme.accent_dark,
    )
    box.pack(fill="x")

    body = tk.Frame(box, bg=theme.panel_bg)
    body.pack(fill="x", padx=8, pady=8)

    message_label = tk.Label(
        body, text="", justify="left", wraplength=280, bg=theme.panel_bg, font=theme.body_font(9),
    )
    message_label.pack(anchor="w")

    def refresh(game_state):
        if game_state is None:
            message_label.config(text="No game in progress.", fg=theme.muted_text)
            return

        advice = suggest_accusation_readiness(game_state)
        message_label.config(
            text=advice.message,
            fg=theme.confirmed if advice.safe_to_accuse else theme.text,
        )

    frame.refresh = refresh
    refresh(None)
    return frame
