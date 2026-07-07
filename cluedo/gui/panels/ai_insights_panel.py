"""AI Insights panel: rule-based behavioral analysis of *other* players'
suggestion patterns (cluedo.analysis.patterns/strategy), shown separately
from the fact panels above it.

This is advisory, never authoritative -- unlike Best Suggestion/Envelope
Probabilities/Statistics (all exact solver output), everything here is a
plain-English guess about playing style, so it's styled deliberately
differently (accent-colored heading, a permanent disclaimer line, and never
theme.confirmed green -- that color means "the solver has proven this",
which no behavioral label ever is) and only reads cluedo.analysis.*, never
cluedo.persistence -- no cross-game history is needed to describe patterns
within the current game.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.patterns import analyze_player_patterns
from cluedo.analysis.strategy import MIN_SUGGESTIONS_FOR_CLASSIFICATION, classify_strategy
from cluedo.gui.widgets import CollapsibleCard

_STRATEGY_LABELS = {
    "room_hunter": "Room Hunter",
    "weapon_hunter": "Weapon Hunter",
    "suspect_hunter": "Suspect Hunter",
    "balanced": "Balanced",
    "aggressive_eliminator": "Aggressive Eliminator",
    "random_explorer": "Random Explorer",
    "bluffer": "Possible Bluffer",
    "information_maximizer": "Information Maximizer",
}


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(
        frame, theme, title="AI Insights", key="ai_insights", fg=theme.accent_dark,
        disclaimer="Advisory only -- behavioral guesses, never certain.",
    )
    card.pack(fill="x")
    body = card.body

    rows_frame = tk.Frame(body, bg=theme.panel_bg)
    rows_frame.pack(fill="x")

    def refresh(game_state):
        for child in rows_frame.winfo_children():
            child.destroy()

        if game_state is None:
            tk.Label(
                rows_frame, text="No game in progress.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        opponents = [p for p in game_state.players if p.seat_index != game_state.user_seat]
        if not opponents:
            tk.Label(
                rows_frame, text="No other players to analyze.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        for player in opponents:
            stats = analyze_player_patterns(game_state, seat=player.seat_index)
            row = tk.Frame(rows_frame, bg=theme.panel_bg)
            row.pack(fill="x", pady=2, anchor="w")
            tk.Label(
                row, text=f"{player.name}:", bg=theme.panel_bg, fg=theme.text,
                font=theme.body_font(9, "bold"), anchor="w",
            ).pack(side="left")

            if stats.total_suggestions < MIN_SUGGESTIONS_FOR_CLASSIFICATION:
                tk.Label(
                    row, text=" not enough data yet", bg=theme.panel_bg, fg=theme.muted_text,
                    font=theme.body_font(9), anchor="w",
                ).pack(side="left")
                continue

            strategy, _evidence = classify_strategy(stats)
            label = _STRATEGY_LABELS.get(strategy.value, strategy.value)
            tk.Label(
                row, text=f" {label}", bg=theme.panel_bg, fg=theme.accent, font=theme.body_font(9), anchor="w",
            ).pack(side="left")

    frame.refresh = refresh
    refresh(None)
    return frame
