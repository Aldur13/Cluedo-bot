"""Warnings panel: flags suggestions that re-asked about a card already
confirmed at the time they were made (cluedo.analysis.patterns.
find_redundant_suggestions) -- for every player, not just the user, since a
redundant ask by an opponent is equally real evidence. Never fabricates a
warning: an empty result is shown plainly as "No warnings", not padded
with speculative content.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.patterns import find_redundant_suggestions
from cluedo.gui.widgets import CollapsibleCard

_CARD_KEY = "warnings"


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Warnings", key=_CARD_KEY, fg=theme.impossible)
    card.pack(fill="x")
    body = card.body

    rows_frame = tk.Frame(body, bg=theme.panel_bg)
    rows_frame.pack(fill="x")

    def _redundant_rows(game_state):
        rows = []
        for player in game_state.players:
            turns = find_redundant_suggestions(game_state, player.seat_index)
            who = "You" if player.seat_index == game_state.user_seat else player.name
            for turn_index in turns:
                suggestion = game_state.history[turn_index]
                rows.append((
                    turn_index,
                    f"Turn {turn_index + 1}: {who} asked about {suggestion.suspect.name}, "
                    f"{suggestion.weapon.name}, or {suggestion.room.name} — already confirmed owned by someone else.",
                ))
        rows.sort(key=lambda pair: pair[0])
        return rows

    def refresh(game_state):
        for child in rows_frame.winfo_children():
            child.destroy()

        if game_state is None or not game_state.history:
            tk.Label(
                rows_frame, text="No warnings.", bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9),
            ).pack(anchor="w")
            return

        rows = _redundant_rows(game_state)
        if not rows:
            tk.Label(
                rows_frame, text="No warnings.", bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9),
            ).pack(anchor="w")
            return

        for _turn_index, message in rows:
            tk.Label(
                rows_frame, text=f"⚠ {message}", bg=theme.panel_bg, fg=theme.impossible, font=theme.body_font(9),
                anchor="w", justify="left", wraplength=280,
            ).pack(anchor="w", pady=2)

    frame.refresh = refresh
    refresh(None)
    return frame
